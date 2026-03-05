"""
Routes to CLI, GUI, or demo based on command-line arguments
"""

import argparse
import pipeline

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
        cli_pipeline = pipeline.Cli(id, simulated)
        pipeline.Cli.orchestrateCli(cli_pipeline, cipher)
    else: 
        pipeline.orchestrateGui()

if __name__ == "__main__":
    main()