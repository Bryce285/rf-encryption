# PySimpleGUI implementation with buttons for Record/Upload, Encrypt, Modulate, Save/Load PCM, Demodulate, Decrypt, Play, and text-to-audio

def start_communication():
    password = password_entry.get()
    encoded_key = generate_key_from_password(password)
    key = get_key_from_password(password, encoded_key)
    key_label.config(text="Encrypted Voice Communication Active")
    key_frame.pack_forget()
    active_frame.pack(fill='both', expand=True)
    main(key, user_mic_device.get(), user_headphones_device.get(), radio_mic_device.get(), radio_headphones_device.get())

def populate_device_list():
    devices = sd.query_devices()
    device_names = [device['name'] for device in devices]
    for device_name in device_names:
        user_mic_device['values'] = device_names
        user_headphones_device['values'] = device_names
        radio_mic_device['values'] = device_names
        radio_headphones_device['values'] = device_names