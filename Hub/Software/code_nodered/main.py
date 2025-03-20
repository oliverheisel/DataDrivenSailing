import subprocess
import time
import logging
import errordebugloggernodered

# initialize logger
logger = logging.getLogger(__name__)

def run_api():
    """
    continuously runs api.py, restarting it if it exits.
    """
    try:
        while True:
            logger.debug("Starting api.py...")
            # start the API as a subprocess
            process = subprocess.Popen(["python", "api.py"])
            # wait for the process to finish (this blocks until it exits)
            process.wait()
            logger.error("api.py terminated with return code %d. Restarting in 5 seconds...", process.returncode)
            time.sleep(5)  # delay before restarting
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down.")

if __name__ == "__main__":
    run_api()
