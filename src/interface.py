"""
Interface module: abstracts audio I/O and simulated RF transmission.
Handles sending/receiving audio signals via physical speakers or the
RF simulation server.
"""

import numpy as np
import numpy.typing as npt
import rfsim_client
import sounddevice as sd

# Default audio sample rate used for playback and recording
SAMPLE_RATE = 48000
# Duration (seconds) of each recording attempt when using real audio input
RECORD_DURATION = 1.0
# RMS below this threshold is treated as silence (no useful signal)
SILENCE_THRESHOLD = 0.01

class Interface:
    """
    Unified send/receive interface that routes audio through either
    a real sounddevice speaker or the simulated RF channel.

    Parameters:
        node_id:    unique identifier for this radio node
        simulated:  if True, also relay through the RF sim server
        speaker_idx: the *original* sounddevice device index for the
                     desired output device (not a filtered-list index)
    """

    def __init__(self, node_id: str, simulated: bool, speaker_idx: int):
        self.SIMULATED = simulated
        self.speaker_idx = speaker_idx  # original sd.query_devices() index

        # Only connect to the simulation server when running in simulated mode
        if self.SIMULATED:
            self.sim_client = rfsim_client.RadioClient(node_id, (0, 0))
        else:
            self.sim_client = None

    # ------------------------------------------------------------------
    # Transmit
    # ------------------------------------------------------------------
    def send(self, msg: npt.NDArray[np.float64], channel: str):
        """
        Transmit an audio signal.

        In simulated mode the signal is both played on the local speaker
        and forwarded to the sim server.  In real mode only local playback
        is performed.

        Parameters:
            msg:     numpy array of audio samples (float64)
            channel: RF channel identifier (used by the sim server)
        """
        # Play the audio on the selected output device
        try:
            sd.play(msg, samplerate=SAMPLE_RATE, device=self.speaker_idx)
            sd.wait()
        except Exception as e:
            print(f"Error during audio playback: {e}")

        # Forward to the simulation server when in simulated mode
        if self.SIMULATED and self.sim_client is not None:
            self.sim_client.channel = channel
            self.sim_client.send(msg)

    # ------------------------------------------------------------------
    # Receive
    # ------------------------------------------------------------------
    def receive(self) -> npt.NDArray[np.float64] | None:
        """
        Receive the next available audio signal.

        In simulated mode this pops the oldest message from the sim
        server inbox.  Returns None when no message is available.

        NOTE: Real (non-simulated) receive is not yet implemented —
              it would require recording from an input device.
        """
        if self.SIMULATED and self.sim_client is not None:
            if self.sim_client.inbox:
                # Pop exactly once and return the signal
                return self.sim_client.inbox.popleft()
            return None
        else:
            # Record a short clip from the default input device and return
            # it if it contains audible signal (above the silence threshold).
            try:
                recording = sd.rec(
                    int(RECORD_DURATION * SAMPLE_RATE),
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype='float64',
                    device=None,       # use default input device
                )
                sd.wait()
                signal = recording.flatten()

                # Discard silent recordings to avoid feeding noise downstream
                rms = np.sqrt(np.mean(signal ** 2))
                if rms < SILENCE_THRESHOLD:
                    return None
                return signal
            except Exception as e:
                print(f"Error recording from microphone: {e}")
                return None