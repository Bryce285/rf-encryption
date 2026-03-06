"""
Modulation module: AFSK (Audio Frequency-Shift Keying) encoding / decoding.

Converts raw bytes into a two-tone audio waveform (mark / space frequencies)
and demodulates the waveform back to bytes using FFT peak detection.
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

    bit_duration = 1 / baud_rate
    samples_per_bit = int(bit_duration * sample_rate)

    t_bit = np.arange(samples_per_bit) / sample_rate
    signal = np.zeros(len(bits) * samples_per_bit)

    for i, bit in enumerate(bits):
        freq = mark_freq if bit == '1' else space_freq
        start = i * samples_per_bit
        end = (i + 1) * samples_per_bit
        signal[start:end] = np.sin(2 * np.pi * freq * t_bit)

    return signal

def afsk_to_text(signal, baud_rate=1200, mark_freq=1200, space_freq=2200, sample_rate=48000):
    """
    Demodulate an AFSK audio signal back into raw bytes.

    Splits the signal into per-bit windows, runs an FFT on each
    window, and classifies the dominant peak as mark or space.

    Returns a bytes object.
    """
    samples_per_bit = int(sample_rate / baud_rate)
    num_bits = len(signal) // samples_per_bit

    bits = ""

    for i in range(num_bits):

        start = i * samples_per_bit
        end = start + samples_per_bit
        chunk = signal[start:end]

        fft = np.abs(np.fft.fft(chunk))
        freq = np.fft.fftfreq(len(chunk), 1 / sample_rate)

        peak_freq = abs(freq[np.argmax(fft)])

        if abs(peak_freq - mark_freq) < abs(peak_freq - space_freq):
            bits += "1"
        else:
            bits += "0"

    data = bytes(
        int(bits[i:i+8], 2)
        for i in range(0, len(bits) - 7, 8)
    )

    return data