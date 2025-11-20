# cs457-ftp-client
FTP client for CS457 project


GOAL:
Implement a Python FTP CLIENT (not server) using TCP sockets only (no external FTP libs).  
Implements RFC959 basics.

FILES:
- ftp_client.py (main)
- Helper modules allowed: ftp_protocol.py, etc.

USER COMMANDS → FTP COMMANDS:
- open <host>    → connect :21
- user <name>    → USER <name>
- pass <pw>      → PASS <pw>
- dir            → LIST
- cd <path>      → CWD <path>
- get <rem>      → RETR <rem>
- put <loc>      → STOR <loc>
- close          → QUIT   (do not exit program)
- quit           → QUIT   (exit)

RESPONSE RULES:
- Must parse: ### single-line
- Must parse: ###- … ### final multiline
- Preliminary = 125 or 150
- Completion = 226 or 250
- Interpret numeric response codes (≥400 = error)

DATA CONNECTION:
- Must use PORT for LIST/RETR/STOR
- PORT a,b,c,d,hi,lo   where:
  hi = port // 256
  lo = port % 256
- After preliminary, create data socket
- Transfer data
- Close data socket
- Then read completion code

TRANSFER MODES:
- TYPE A before LIST
- TYPE I before RETR/STOR
- Binary files supported

THREADS:
- Use threading for command+data / responsiveness

IMPLEMENTATION ORDER:
1) control connect
2) USER
3) PASS
4) single-line parse
5) multiline parse
6) numeric decode
7) PORT helper
8) LIST
9) CWD
10) RETR
11) STOR
12) QUIT/close handling
13) threading
14) error handling

CONSTRAINTS:
- Python stdlib only (`socket`, `threading`, etc)
- Produce runnable code
- Direct text output to stdout
- Keep logic explicit / minimal abstraction

PATCH FORMAT (preferred):
Provide patch blocks:
```patch
--- a/file
+++ b/file
@@
...

