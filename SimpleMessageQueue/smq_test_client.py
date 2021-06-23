# --------------------------------------------------
#    Imports
# --------------------------------------------------
import logging
import os
import socket
import threading
import time
from pylinkjs.PyLinkJS import run_pylinkjs_app, get_broadcast_jsclients
from SimpleMessageQueue import SMQServer, SMQClient


# --------------------------------------------------
#    Globals
# --------------------------------------------------
SMQC = {}


# --------------------------------------------------
#    Functions
# --------------------------------------------------
def ready(jsc, *args):
    print('READY!')
    jsc['#td_hostname'].html = socket.gethostname()
    jsc['#td_pid'].html = os.getpid()


def reconnect(jsc, *args):
    print('RECONNECT!')
    jsc['#td_hostname'].html = socket.gethostname()
    jsc['#td_pid'].html = os.getpid()


def button_start_clicked(jsc):
    smq_server = jsc['#text_smqserver'].val
    client_name = jsc['#name'].val
    pub_list = jsc['#text_publist'].val
    sub_list = jsc['#text_sublist'].val

    SMQC[jsc] = SMQC.get(jsc, SMQClient())
    SMQC[jsc].start_client(smq_server, client_name, pub_list, sub_list)


def button_stop_clicked(jsc):
    response = SMQC[jsc].shutdown()
    jsc['#td_start_stop_response'].html = str(response)


def button_test(jsc):
    t = time.time()
    for bjsc in jsc.get_broadcast_jscs():
        bjsc['#pre'].html = t


def button_check_new_messages_clicked(jsc):
    msg_tuple = SMQC[jsc].get_message()
    jsc['#received_message'].html = str(msg_tuple)


def button_publish_clicked(jsc):
    msg = jsc['#text_message'].val
    msg_data = jsc['#text_data'].val
    response = SMQC[jsc].publish_message(msg, msg_data)
    jsc['#td_response'].html = str(response)


def thread_worker():
    while True:
        time.sleep(5)
        t = time.time()
        try:
            for jsc in get_broadcast_jsclients('/a.html'):
                jsc['#pre'].html = t
        except Exception as _:
            pass


# --------------------------------------------------
#    Main
# --------------------------------------------------
if __name__ == "__main__":
    # just to make life easier, let's start a SMQServer in a different thread
    SMQServer.start_in_thread(('localhost', 7000))

    t = threading.Thread(target=thread_worker, daemon=True)
    t.start()

    logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    run_pylinkjs_app(default_html='smq_test_client.html', port=7001)
