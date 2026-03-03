# covert bytes into two-tone audio, demodulate back to bits, multi-tone audio encoding

import numpy as np

def text_to_afsk(text, baud_rate=1200, mark_freq=1200, space_freq=2200, sample_rate=48000):
    bits = ''.join(format(ord(c), '08b') for c in text)
    bit_duration = 1 / baud_rate
    t = np.arange(0, len(bits) * bit_duration, 1 / sample_rate)
    signal = np.zeros_like(t)
    for i, bit in enumerate(bits):
        freq = mark_freq if bit == '1' else space_freq
        signal[i * int(bit_duration * sample_rate):(i + 1) * int(bit_duration * sample_rate)] = np.sin(2 * np.pi * freq * t[:int(bit_duration * sample_rate)])
    return signal

def afsk_to_text(signal, baud_rate=1200, mark_freq=1200, space_freq=2200, sample_rate=48000):
    bit_duration = 1 / baud_rate
    num_bits = int(len(signal) / (bit_duration * sample_rate))
    bits = ''
    for i in range(num_bits):
        chunk = signal[i * int(bit_duration * sample_rate):(i + 1) * int(bit_duration * sample_rate)]
        freq = np.fft.fftfreq(len(chunk), 1 / sample_rate)
        fft = np.abs(np.fft.fft(chunk))
        peak_freq = freq[np.argmax(fft)]
        if abs(peak_freq - mark_freq) < abs(peak_freq - space_freq):
            bits += '1'
        else:
            bits += '0'
    text = ''.join(chr(int(bits[i:i + 8], 2)) for i in range(0, len(bits), 8))
    return text