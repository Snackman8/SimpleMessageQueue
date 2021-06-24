import argparse
import logging
import traceback
from SimpleMessageQueue import SMQServer


# --------------------------------------------------
#    Main
# --------------------------------------------------
def _init_logging():
    # setup logging
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(threadName)s %(message)s'))
    root.addHandler(console_handler)

    # rely on systemd to write log to file
    # file_handler = logging.FileHandler(filename='simple_message_queue.log')
    # file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(threadName)s %(message)s'))
    # root.addHandler(file_handler)


def run(args):
    if args['start_server']:
        logging.info(f'Starting Simple Message Queue Server at {args["server_hostname"]}:{args["server_port"]}')
        SMQServer._thread_worker((args['server_hostname'], args['server_port']), (), {})


if __name__ == "__main__":
    # init the loggers
    _init_logging()

    try:
        # parse the arguments
        parser = argparse.ArgumentParser(description='SimpleMessageQeue')
        parser.add_argument('--start_server', help='filename of config file to use, i.e. cfg_test.py',
                            action='store_true')
        parser.add_argument('--server_hostname', required=True)
        parser.add_argument('--server_port', required=True, type=int)
        parser.add_argument('--log_level', default=logging.INFO)
        args = parser.parse_args()

        # switch logging level
        root = logging.getLogger()
        root.setLevel(args.log_level)

        # run
        run(vars(args))
    except Exception:
        logging.error(traceback.format_exc())
