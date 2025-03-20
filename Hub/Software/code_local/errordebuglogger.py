import logging
from logging.handlers import RotatingFileHandler
from modules import led  # this module should provide led.trigger_error()
from config import config  # config.log_debug is used to control debug logging
import os

def rollover(handler, max_entries=1000, delete_count=250):
    """
    rollover: when the log file has reached max_entries,
    delete the oldest delete_count entries (lines) from the file.
    """
    # flush and close the current stream
    if handler.stream:
        handler.stream.flush()
        handler.stream.close()
    try:
        with open(handler.baseFilename, 'r') as f:
            lines = f.readlines()
    except Exception:
        lines = []  
    # remove the oldest delete_count lines
    new_lines = lines[delete_count:]
    with open(handler.baseFilename, 'w') as f:
        f.writelines(new_lines)
    # reopen the file and update the entry counter based on the new content
    handler.stream = open(handler.baseFilename, handler.mode)
    handler._entry_count = len(new_lines)

def patch_handler(handler, max_entries=1000, delete_count=250, trigger_led_error=False):
    """
    patch handler's emit method to count entries.
    when the count reaches max_entries, perform the rollover.
    if trigger_led_error is true, call led.trigger_error() for each record
    that is logged at error level or higher.
    """
    handler._entry_count = 0  # initialize a counter on the handler
    original_emit = handler.emit  # keep the original emit method

    def new_emit(record):
        original_emit(record)
        handler._entry_count += 1
        if trigger_led_error and record.levelno >= logging.ERROR:
            # trigger the led error (once per error record)
            led.trigger_error()
        if handler._entry_count >= max_entries:
            rollover(handler, max_entries, delete_count)
    handler.emit = new_emit

# define a filter function to exclude records with a level of error or higher
def max_level_filter(record):
    return record.levelno < logging.ERROR

# assign the function's filter attribute to itself so it behaves like a filter object
max_level_filter.filter = max_level_filter

def log(debug_log_file='debug.log', error_log_file='error.log',
        debug=True, max_entries=1000, delete_count=250):
    """
    sets up two file handlers:
      - one for debug (and below error) messages in debug_log_file.
      - one for error (and above) messages in error_log_file.
    
    when either file reaches max_entries, the oldest delete_count lines are removed.
    the error handler additionally triggers the led error via led.trigger_error().
    """
    # ensure the logfiles directory exists and update log file paths
    log_dir = 'logfiles'
    os.makedirs(log_dir, exist_ok=True)
    debug_log_file = os.path.join(log_dir, debug_log_file)
    error_log_file = os.path.join(log_dir, error_log_file)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # debug handler (for messages below error)
    debug_handler = RotatingFileHandler(debug_log_file, mode='a', maxBytes=0, backupCount=0)
    patch_handler(debug_handler, max_entries, delete_count, trigger_led_error=False)
    debug_handler.setLevel(logging.DEBUG)
    # add filter to allow only messages below error level
    debug_handler.addFilter(max_level_filter)
    debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    debug_handler.setFormatter(debug_formatter)
    logger.addHandler(debug_handler)
    
    # error handler (for error and above messages)
    error_handler = RotatingFileHandler(error_log_file, mode='a', maxBytes=0, backupCount=0)
    patch_handler(error_handler, max_entries, delete_count, trigger_led_error=True)
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)

# automatically configure logging when this module is imported
log(debug_log_file='debug.log', error_log_file='error.log',
    debug=config.log_debug, max_entries=1000, delete_count=250)
