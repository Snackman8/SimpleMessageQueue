# --------------------------------------------------
#    Imports
# --------------------------------------------------
import argparse
from collections import deque
import logging
import os
import socket
import threading
import traceback
import uuid
from xmlrpc.server import SimpleXMLRPCServer
import xmlrpc.client
from socketserver import ThreadingMixIn
from concurrent.futures import ThreadPoolExecutor


# --------------------------------------------------
#    Extended SimpleXMLRPCServer
# --------------------------------------------------
class SimpleXMLRPCServerEx(ThreadingMixIn, SimpleXMLRPCServer):
    def __init__(self, addr, *args, **kwargs):
        super().__init__(addr, *args, **kwargs)
        self._shutdown = False

    def shutdown(self):
        self._shutdown = True

    def serve_forever(self):
        self.timeout = 0.1
        while not self._shutdown:
            self.handle_request()


# --------------------------------------------------
#    Server
# --------------------------------------------------
class SMQServer():
    def __init__(self):
        # init
        self._clients = {}

    def publish_message(self, client_info, msg, msg_data, direct_smq_uid=None):
        try:
            # sanity check
            cuid = client_info['smq_uid']
            if cuid not in self._clients:
                logging.warning('Received message from client %s that is not registered' % cuid)

            # verify the message is in the pub list
            if msg not in self._clients[cuid]['pub_list']:
                logging.error('%s is not in the pub_list of %s' % (msg, client_info['smq_uid']))
                raise Exception('%s is not in the pub_list of %s' % (msg, client_info['smq_uid']))

            # loop is more complex because may be operating in concurrent threads
            logging.info(f'Publishing message {msg} from {client_info["smq_uid"]}')
            client_ids = list(self._clients.keys())
            for c in client_ids:
                if direct_smq_uid and c != direct_smq_uid:
                    continue

                ci = self._clients.get(c, None)
                if ci is None:
                    continue

                # publish to any clients on the sub list
                if msg in ci['sub_list']:
                    logging.info(f'Forwarding message {msg} to {c}')
                    try:
                        ci['client_rpc_server'].receive_message(cuid, msg, msg_data)
                    except ConnectionRefusedError:
                        logging.info(f'Removing client {c} because connection refused')
                        # this may fail if another thread deletes at the same time
                        try:
                            del self._clients[c]
                        except Exception:
                            pass
        except Exception as e:
            logging.error(traceback.format_exc())
            raise(e)

    def register_client(self, client_info):
        try:
            logging.info(f'Registering Client {client_info["smq_uid"]} {client_info["client_name"]} ' +
                         f'{client_info["client_hostname"]} {client_info["client_pid"]}')

            # sanity check
            cuid = client_info['smq_uid']
            if cuid in self._clients:
                logging.error(f'Client {cuid} already registered')
                raise Exception('Error!  Client %s already registered' % cuid)

            # save the client info
            self._clients[cuid] = client_info

            # preprocess the pub and sub lists
            self._clients[cuid]['pub_list'] = set(self._clients[cuid]['pub_list_str'].split())
            self._clients[cuid]['sub_list'] = set(self._clients[cuid]['sub_list_str'].split())

            # create a proxy to the client rpc server
            self._clients[cuid]['client_rpc_server'] = xmlrpc.client.ServerProxy(
                'http://' + client_info['client_rpc_url'], allow_none=True)
        except Exception as e:
            logging.info(traceback.format_exc())
            raise(e)

    def unregister_client(self, client_info):
        # remove client from the clients list
        logging.info(f'unregistering {client_info["client_name"]} {client_info["smq_uid"]}')
        del self._clients[client_info['smq_uid']]

    @classmethod
    def _thread_worker(cls, addr, args, kwargs):
        kwargs['allow_none'] = kwargs.get('allow_none', True)
        kwargs['logRequests'] = kwargs.get('logRequests', False)
        server_impl = SMQServer()
        server = SimpleXMLRPCServerEx(addr, *args, **kwargs)
        server.register_instance(server_impl)
        server.serve_forever()

    @classmethod
    def start_in_thread(cls, addr, *args, **kwargs):
        t = threading.Thread(target=cls._thread_worker, args=(addr, args, kwargs), daemon=True)
        t.start()


# --------------------------------------------------
#    Client
# --------------------------------------------------
class SMQClient():
    def __init__(self):
        # init
        self._client_info = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._local_rpc_server = None
        self._local_rpc_server_thread = None
        self._message_handler = None
        self._message_queue = deque()
        self._smq_server = None

    def start_client(self, smq_server, client_name, pub_list_str, sub_list_str, message_handler=None):
        # sanity check
        if self._local_rpc_server:
            raise Exception('Client already started')

        logging.info('Starting Client...')

        # set start flag
        self._message_handler = message_handler

        # init the rpc to the main smq server
        self._smq_server = xmlrpc.client.ServerProxy('http://' + smq_server, allow_none=True)

        # start XML RPC server on new thread
        self._local_rpc_server = SimpleXMLRPCServerEx(('', 0), allow_none=True, logRequests=False)
        self._local_rpc_server.register_function(self.receive_message)
        self._local_rpc_server_thread = threading.Thread(target=lambda: self._local_rpc_server.serve_forever(),
                                                         daemon=True)
        self._local_rpc_server_thread.start()

        # register this client with the main smq server
        client_rpc_url = socket.gethostname() + ':' + str(self._local_rpc_server.server_address[1])
        self._client_info = {'client_name': client_name, 'pub_list_str': pub_list_str, 'sub_list_str': sub_list_str,
                             'client_hostname': socket.gethostname(), 'client_pid': os.getpid(),
                             'client_rpc_url': client_rpc_url, 'smq_uid': uuid.uuid4().hex}
        logging.info(self._client_info)
        self._smq_server.register_client(self._client_info)

    def publish_message(self, msg, msg_data):
        # publish message to main smq server
        logging.info(f'Publishing Message "{msg}"')
        self._smq_server.publish_message(self._client_info, msg, msg_data)

    def send_direct_message(self, smq_uid, msg, msg_data):
        # send a direct message to a specific client
        logging.info(f'Sending Direct Message "{msg}" to {smq_uid}')
        self._smq_server.publish_message(self._client_info, msg, msg_data, smq_uid)

    def receive_message(self, sender_smq_uid, msg, msg_data):
        # receive message from main smq server
        logging.info(f'Received Message "{msg}"')
#         if self._client_info['smq_uid'] != smq_uid:
#             logging.warning('Mismatched client UID')
#             return
        kwargs = {'smq_uid': sender_smq_uid, 'msg': msg, 'msg_data': msg_data}
        self._message_queue.append(kwargs)
        if self._message_handler:
            self._executor.submit(self._message_handler, **kwargs)

    def get_message(self):
        if self._message_queue:
            return self._message_queue.popleft()

    def shutdown(self):
        """ shutdown the SMQ client """
        # sanity check
        logging.info('smq client shutdown')
        if not self._started:
            raise Exception('Client not started')
        self._smq_server.unregister_client(self._client_info)
        self._local_rpc_server.shutdown()
        self._local_rpc_server_thread.join()
        self._local_rpc_server_thread = None
        self._client_info = None
        self._local_rpc_server = None
        self._smq_server = None
        self._started = False
