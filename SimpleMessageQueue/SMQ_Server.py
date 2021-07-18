# --------------------------------------------------
#    Imports
# --------------------------------------------------
import argparse
import logging
import multiprocessing
import queue
import threading
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler


# --------------------------------------------------
#    Class
# --------------------------------------------------
class SMQ_Server():
    def __init__(self, hostname, port):
        """ init """
        self._dispatch_thread = None
        self._hostname = hostname
        self._mp_manager = multiprocessing.Manager()
        self._port = port
        self._registered_clients = {}
        self._rpc_server = None
        self._shutdown = False

        # create our incoming queue
        self._incoming_queue = self._mp_manager.Queue()

    def _tw_dispatch(self):
        while not self._shutdown:
            try:
                msg = self._incoming_queue.get(block=True, timeout=0.1)
                if msg['target_id'] == '*':
                    targets = self._registered_clients.keys()
                else:
                    targets = [msg['target_id']]
                for t in targets:
                    if t in self._registered_clients:
                        logging.info(f'Dispatching {msg["msg_uuid"]} {msg["msg_type"]} {msg["payload"]} ' +
                                     f'from {msg["sender_id"]} to {t}')
                        self._registered_clients[t]['incoming_queue'].put(msg, block=False)
                        logging.info(f'Dispatched')
            except queue.Empty:
                pass
            except Exception as e:
                logging.exception(e)

    def get_info_for_all_clients(self):
        """
            return information about all registered clients

            Returns:
                {client_id: {'client_name': client_name, 'classifications': classifications, 'pub_list': pub_list,
                             'sub_list': sub_list}
                 ...}
        """
        client_info = {}
        for k, v in self._registered_clients.items():
            client_info[k] = {kk: v[kk] for kk in ('client_name', 'classifications', 'pub_list', 'sub_list', 'tag')}
        return client_info

    def pop_message(self, client_id):
        """ pop a message from the incoming_queue for the client_id

            Args:
                client_id - client_id of the queue to check

            Returns:
                msg if available or None if no message is available
        """
        try:
            msg = self._registered_clients[client_id]['incoming_queue'].get(block=False)
            logging.info(f'Message popped {client_id} {msg["msg_type"]}')
            return msg
        except queue.Empty:
            return None
        except Exception as e:
            logging.exception(e)

    def register_client(self, client_name, client_id, classifications, pub_list, sub_list, tag):
        """
            register a client with the SMQ Server

            Args:
                client_name - displayable name of the client
                client_id - unique ID of this client
                classifications - list of items classifying this client, i.e. ['FlowController', 'test.cfg']
                pub_list - list of messages published by this client, i.e. ['ping', 'reload']
                sub_list - list of messages subscribed by this client, i.e. ['ping_response', 'reload_response']
        """
        hostname = '?'
        for i in range(0, 10):
            try:
                f = sys._getframe(i)
                if isinstance(f.f_locals['self'], SimpleXMLRPCRequestHandler):
                    hostname = f.f_locals['self'].client_address
                    break
            except Exception as _:
                pass
        logging.info(f'Registering Client {hostname} {client_name} {client_id} {classifications} {pub_list} ' +
                     f'{sub_list} {tag}')

        client_incoming_queue = self._mp_manager.Queue()
        self._registered_clients[client_id] = {'client_name': client_name, 'classifications': classifications,
                                               'pub_list': pub_list, 'sub_list': sub_list, 'hostname': hostname,
                                               'incoming_queue': client_incoming_queue, 'tag': tag}

    def shutdown(self):
        """ called by rpc to shutdown this SMQ Server """
        logging.info('Shutting down server')

        # shutdown the RPC
        t = threading.Thread(target=lambda: self._rpc_server.shutdown())
        t.start()
        self._shutdown = True

    def start(self):
        """ start the RPC server for the SMQ_Server using the port passed in in __init__

            register functions for get_info_for_all_clients
                                   pop_message
                                   register_client
                                   send_message
                                   shutdown
                                   unregister_client
        """
        logging.info(f'Starting SMQ Server Dispatch Thread')
        self._dispatch_thread = threading.Thread(target=self._tw_dispatch)
        self._dispatch_thread.start()

        logging.info(f'Starting SMQ Server RPC on port {self._port}')
        self._rpc_server = SimpleXMLRPCServer(('', self._port), allow_none=True, logRequests=False)
        self._rpc_server.register_function(self.get_info_for_all_clients)
        self._rpc_server.register_function(self.pop_message)
        self._rpc_server.register_function(self.register_client)
        self._rpc_server.register_function(lambda msg: self._incoming_queue.put(msg, block=False), name='send_message')
        self._rpc_server.register_function(self.shutdown)
        self._rpc_server.register_function(self.unregister_client)
        self._rpc_server.serve_forever()

    def unregister_client(self, client_id):
        """
            unregisters a client with the SMQ Server

            Args:
                client_id - unique ID of the client to unregister
        """
        logging.info(f'Unregistering Client {client_id}')
        if client_id in self._registered_clients:
            logging.info(f'Deleting Client {client_id}')
            del self._registered_clients[client_id]


# --------------------------------------------------
#    Main
# --------------------------------------------------
def run(args):
    """ run """
    # start the server
    if args['start_server']:
        server = SMQ_Server(args['hostname'], args['port'])
        server.start()


if __name__ == "__main__":
    try:
        # parse the arguments
        parser = argparse.ArgumentParser(description='Simple Message Queue Server')
        parser.add_argument('--hostname', required=True, help='hostname to run SMQ Server on')
        parser.add_argument('--port', type=int, required=True, help='port to run SMQ Server on')
        parser.add_argument('--start_server', action='store_true', help='start the SMQ Server')
        parser.add_argument('--logging_level', default='INFO', help='logging level')
        args = parser.parse_args()

        # setup logging
        logging.basicConfig(level=logging.getLevelName(args.logging_level),
                            format='%(asctime)s %(levelname)s %(threadName)s %(message)s')
        logging.info('Starting ', vars(args))

        # run
        run(vars(args))
    except Exception as e:
        logging.exception('Exception')
        raise(e)
