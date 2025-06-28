import subprocess
import platform
import logging

# initialize logger
logger = logging.getLogger(__name__)

def ping_device(device, timeout=2):
    """
    pings the specified device with a timeout.
    
    :param device: hostname or IP address of the device to ping.
    :param timeout: timeout in seconds before considering it unreachable.
    :return: dictionary {"id": device, "ping": True/False}
    """
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'

    command = ['/usr/bin/ping', param, '1', timeout_param, str(timeout), device]

    try:
        response = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        success = response.returncode == 0
        logger.debug("ping_device_success: %s -> %s", device, success)
    except subprocess.TimeoutExpired:
        logger.error("ping_device_timeout: %s", device)
        success = False
    except Exception as e:
        logger.error("ping_device_error: %s -> %s", device, str(e))
        success = False

    return {"id": device, "ping": success}

if __name__ == "__main__":
    device = "boat1.local"
    result = ping_device(device)
    logger.debug("Final result: %s", result)