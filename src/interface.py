import numpy as np
import numpy.typing as npt
import rfsim_client
import sounddevice as sd

class Interface:
    def __init__(self, id: str, SIMULATED: bool, speakerID: int):
        self.sim_client = rfsim_client.RadioClient(id, (0,0))
        self.SIMULATED = SIMULATED
        self.speakerID = speakerID

    def send(self, msg: npt.NDArray[np.float64], channel: str):
        devices = sd.query_devices()
        output_devices = [d for d in devices if d['max_output_channels'] > 0]
        
        if self.SIMULATED:
            try:
                sd.play(msg, samplerate=48000, device=output_devices[self.speakerID])
            except Exception as e:
                print(f"Error during transmission: {e}")
            self.sim_client.channel = channel
            self.sim_client.send(msg)
        else:
            try:
                sd.play(msg, samplerate=48000, device=output_devices[self.speakerID])
            except Exception as e:
                print(f"Error during transmission: {e}")

    def receive(self) -> npt.NDArray[np.float64]:
        devices = sd.query_devices()
        output_devices = [d for d in devices if d['max_output_channels'] > 0]
        
        if self.SIMULATED and self.sim_client.inbox:
            try:
                sd.play(self.sim_client.inbox.popleft(), samplerate=48000, device=output_devices[self.speakerID])
            except Exception as e:
                print(f"Error processing message: {e}")
            return self.sim_client.inbox.popleft()
        else:
            try:
                sd.play(self.sim_client.inbox.popleft(), samplerate=48000, device=output_devices[self.speakerID])
            except Exception as e:
                print(f"Error processing message: {e}")