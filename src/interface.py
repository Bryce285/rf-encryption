
import numpy as np
import numpy.typing as npt
import rfsim_client

class Interface:
    def __init__(self, id: str, SIMULATED: bool):
        self.sim_client = rfsim_client.RadioClient(id, (0,0))
        self.SIMULATED = SIMULATED

    def send(self, msg: npt.NDArray[np.float64], channel: str):
        if self.SIMULATED:
            self.sim_client.channel = channel
            self.sim_client.send(msg)
        else:
            # TODO implement interface for real hardware
            pass

    def receive(self) -> npt.NDArray[np.float64]:
        if self.SIMULATED and self.sim_client.inbox:
            return self.sim_client.inbox.popleft()
        else:
            # TODO implement interface for real hardware
            pass