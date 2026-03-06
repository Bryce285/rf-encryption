"""
Routes to CLI, GUI, or demo based on command-line arguments
"""

import argparse
import pipeline
import sounddevice as sd

def main():
    parser = argparse.ArgumentParser(description="My Messaging App")

    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch with GUI enabled"
    )

    parser.add_argument(
        "--cipher",
        choices=["aes", "rsa"],
        required=True,
        help="Cipher to use"
    )

    parser.add_argument(
        "--id",
        type=str,
        required=True,
        help="Set the id that other users will see"
    )

    parser.add_argument(
        "--simulated",
        action="store_true",
        help="Send messages over simulated RF connection using the sim server"
    )

    args = parser.parse_args()

    gui = args.gui
    cipher = args.cipher
    id = args.id
    simulated = args.simulated

    if gui == False:
        
        # Get all audio devices
        devices = sd.query_devices()
        
        # Filter for output devices
        output_devices = [d for d in devices if d ['max_output_channels'] > 0]
        
        print("Please select your desired output device:")
        
        for i, device in enumerate(output_devices):
            print(f"{i}: {device['name']}")
            
        speakerID = int(input("\nEnter device number: "))
        
        cli_pipeline = pipeline.Cli(id, simulated, speakerID)
        pipeline.Cli.orchestrateCli(cli_pipeline, cipher)
    else: 
        pipeline.orchestrateGui()

if __name__ == "__main__":
    main()