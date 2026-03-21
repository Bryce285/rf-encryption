"""
Modulation module: AFSK (Audio Frequency-Shift Keying) encoding / decoding.

Converts raw bytes into a two-tone audio waveform (mark / space frequencies)
and demodulates the waveform back to bytes using FFT peak detection.

This implementation of modulation is based on an implementation from a 
similar radio encryption project made by Unlimited Research Cooperative, which 
can be found at: https://github.com/Unlimited-Research-Cooperative/AES256-radio
"""

import numpy as np

# Default parameters
#   baud_rate  : symbol rate in bits/s
#   mark_freq  : frequency representing a '1' bit (Hz)
#   space_freq : frequency representing a '0' bit (Hz)
#   sample_rate: audio samples per second


def text_to_afsk(data, baud_rate=1200, mark_freq=1200, space_freq=2200, sample_rate=48000):
    """
    Modulate *data* (bytes or str) into an AFSK audio signal.

    Each byte is expanded to 8 bits; each bit becomes a burst of
    sine-wave at either *mark_freq* (1) or *space_freq* (0).

    Returns a numpy float64 array of audio samples.
    """
    if isinstance(data, str):
        data = data.encode()

    bits = ''.join(format(byte, '08b') for byte in data)
    samples_per_bit = int(sample_rate / baud_rate)
    t_bit = np.arange(samples_per_bit) / sample_rate

    freqs = np.array([mark_freq if b == '1' else space_freq for b in bits])

    t_all = np.tile(t_bit, len(bits))
    freq_all = np.repeat(freqs, samples_per_bit)
    return np.sin(2 * np.pi * freq_all * t_all)

def afsk_to_text(signal, baud_rate=1200, mark_freq=1200, space_freq=2200, sample_rate=48000):
    """
    Demodulate an AFSK audio signal back into raw bytes.

    Splits the signal into per-bit windows, runs an FFT on each
    window, and classifies the dominant peak as mark or space.

    Returns a bytes object.
    """
    samples_per_bit = int(sample_rate / baud_rate)
    num_bits = len(signal) // samples_per_bit

    bits = []
    for i in range(num_bits):
        chunk = signal[i * samples_per_bit:(i + 1) * samples_per_bit]
        fft_mag = np.abs(np.fft.fft(chunk))
        freqs = np.fft.fftfreq(len(chunk), 1 / sample_rate)
        peak = abs(freqs[np.argmax(fft_mag)])
        bits.append('1' if abs(peak - mark_freq) < abs(peak - space_freq) else '0')

    bitstring = ''.join(bits)
    return bytes(
        int(bitstring[i:i + 8], 2)
        for i in range(0, len(bitstring) - 7, 8)
    )