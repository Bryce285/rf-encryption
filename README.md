# rf-encryption

rf-encryption is a small Python project that simulates sending encrypted messages over a radio-frequency (RF)-like channel. It combines simple cryptography, framing, and modulation primitives with a simulated server and client so you can test end-to-end message flow. The codebase is organized into modules for encryption (`src/crypto.py`), framing (`src/framing.py`), modulation (`src/modulation.py`), protocol/pipeline handling, and includes both command-line and basic GUI entry points. This project is intended for learning and experimentation rather than production use.

## TODO

- add logger/remove debug prints
- improve rf simulation
- get real audio working if possible
- get GUI working if possible
- replace "RECEIVED MESSAGE" with connected peer's ID (e.g. "Alice says ->")
