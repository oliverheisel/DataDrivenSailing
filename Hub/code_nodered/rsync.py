import subprocess
import os
import sys
import logging
from pingcheck import ping_device

# initialize logger
logger = logging.getLogger(__name__)

# set timeout values
PING_TIMEOUT = 2  # timeout in seconds for ping
RSYNC_TIMEOUT = 10  # timeout in seconds for rsync

def ensure_directory_exists(directory):
    """
    ensure the destination directory exists. If not, create it with sudo rights.
    
    :param directory: path to the directory that needs to exist.
    """
    if not os.path.exists(directory):
        logger.debug("Creating directory: %s (sudo required)", directory)
        try:
            subprocess.run(["sudo", "mkdir", "-p", directory], check=True, timeout=5)
            subprocess.run(["sudo", "chown", os.getlogin(), directory], check=True, timeout=5)
            logger.debug("Directory created: %s", directory)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to create directory: %s", str(e))
            sys.exit(1)

def rsync_data(device, options="-avz"):
    """
    synchronize data from a remote device to the local destination using rsync.
    
    :param device: the name of the remote device (e.g., "boat1").
    :param options: rsync options (default: "-avz").
    :return: a dictionary with the sync status and output or error message.
    """
    destination = "/home/globaladmin/IOTstack/volumes/nodered/data/datarsync"

    # ensure the device ends with ".local"
    if not device.endswith(".local"):
        device += ".local"

    # extract the device name without ".local"
    device_id = device.replace(".local", "")

    # ping the device with timeout before proceeding
    ping_result = ping_device(device, timeout=PING_TIMEOUT)
    if not ping_result["ping"]:
        logger.error("Device %s is unreachable. Aborting rsync.", device)
        return {"id": device_id, "status": "error", "error": f"Device {device} is unreachable."}

    logger.debug("Device %s is reachable. Proceeding with rsync...", device)

    # correct rsync source format: user@host:/path/to/file
    source = f"globaladmin@{device}:/home/globaladmin/data/datalog_{device_id}.db"

    # ensure the destination directory exists
    ensure_directory_exists(destination)

    # construct the rsync command
    cmd = ["/usr/bin/rsync", "-e", "/usr/bin/ssh"] + options.split() + [source, destination]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True, timeout=RSYNC_TIMEOUT)
        logger.debug("Rsync successful: %s", result.stdout)
        return {"id": device_id, "status": "success", "output": result.stdout}
    except subprocess.TimeoutExpired:
        logger.error("Rsync timed out after %d seconds.", RSYNC_TIMEOUT)
        return {"id": device_id, "status": "error", "error": f"Rsync timed out after {RSYNC_TIMEOUT} seconds."}
    except subprocess.CalledProcessError as e:
        logger.error("Rsync failed: %s", e.stderr)
        return {"id": device_id, "status": "error", "error": e.stderr}

if __name__ == "__main__":
    # default values for testing
    device = "boat1"  # input hostname
    result = rsync_data(device)
    logger.debug("Final result: %s", result)
