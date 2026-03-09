"""
Entry point: routes to CLI or GUI based on command-line arguments.

Usage examples:
    python main.py --cipher aes --id alice              # CLI mode
    python main.py --cipher aes --id alice --gui        # GUI mode
    python main.py --cipher aes --id alice --simulated  # use RF sim server
"""

import argparse
import pipeline
import sounddevice as sd


def main():
    parser = argparse.ArgumentParser(description="RF Encrypted Messaging App")

    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch with GUI enabled"
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

    # Avoid shadowing the built-in `id`
    node_id = args.id
    simulated = args.simulated

    if not args.gui:
        # ----- CLI mode -----
        # List all audio output devices so the user can choose one.
        # We keep the *original* device index (position in sd.query_devices())
        # because sd.play(device=…) requires that original index.
        devices = sd.query_devices()

        output_devices = [
            (i, d) for i, d in enumerate(devices)
            if d['max_output_channels'] > 0
        ]

        print("Please select your desired output device:")
        for idx, (original_idx, device) in enumerate(output_devices):
            print(f"  {idx}: {device['name']}  (device #{original_idx})")

        selection = int(input("\nEnter device number: "))

        # Resolve the user's selection back to the original device index
        speaker_idx = output_devices[selection][0]

        cli_pipeline = pipeline.Cli(node_id, simulated, speaker_idx)
        cli_pipeline.orchestrateCli()
    else:
        # ----- GUI mode -----
        pipeline.orchestrateGui()


if __name__ == "__main__":
    main()