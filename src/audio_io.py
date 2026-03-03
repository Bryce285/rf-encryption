# Recording, playback, loading/saving PCM files, audio device management

import framing, modulation
import sounddevice as sd
import numpy as np

# Live transmitting and receiving functions
def transmit_message(key, user_mic, radio_mic, radio_output):
    def callback(indata, frames, time, status):
        if status:
            print(status)
        try:
            message = encrypt_message(indata.tobytes(), key)
            rs_encoded_message = framing.encode_reed_solomon(message)
            preamble_message = framing.add_preamble(rs_encoded_message)
            afsk_signal = modulation.text_to_afsk(preamble_message)
            sd.play(afsk_signal, samplerate=48000, device=radio_output)
        except Exception as e:
            print(f"Error during transmission: {e}")

    with sd.InputStream(callback=callback, channels=1, device=radio_mic):
        sd.sleep(-1)  # Runs indefinitely

def receive_message(key, radio_input, user_output):
    def callback(indata, frames, time, status):
        if status:
            print(status)
        received_signal = indata.flatten()
        received_message = modulation.afsk_to_text(received_signal)
        try:
            preamble_removed_message = framing.remove_preamble(received_message)
            rs_decoded_message = framing.decode_reed_solomon(preamble_removed_message)
            decrypted_message = decrypt_message(rs_decoded_message, key)
            sd.play(np.frombuffer(decrypted_message, dtype=np.int16), samplerate=48000, device=user_output)
        except Exception as e:
            print(f"Error decoding message: {e}")
    
    with sd.InputStream(callback=callback, channels=1, device=radio_input):
        sd.sleep(-1)  # Runs indefinitely