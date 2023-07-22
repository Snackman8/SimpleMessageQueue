# --------------------------------------------------
#    Imports
# --------------------------------------------------
import logging
import threading
import time
import xmlrpc.client
from xmlrpc.server import SimpleXMLRPCServer
import uuid


# --------------------------------------------------
#    Class
# --------------------------------------------------
class SMQ_Client():
    def __init__(self, smq_server_url, client_name, client_id, classifications, pub_list, sub_list, tag={},
                 polling_interval=0.1):
        """ init """
        self._alive_rpc_server = None
        self._classification = classifications
        self._client_id = client_id
        self._client_name = client_name
        self._incoming_queue = None
        self._message_handlers = {}
        self._outgoing_queue = None
        self._polling_interval = polling_interval
        self._pub_list = pub_list
        self._pub_list_extended = pub_list + [f'{x}_response' for x in sub_list]
        self._response_callbacks = {}
        self._shutdown = False
        self._smq_server_url = smq_server_url
        self._started = False
        self._sub_list = sub_list
        self._sub_list_extended = sub_list + [f'{x}_response' for x in pub_list]
        self._tag = tag

    def __del__(self):
        """ unregister client when this instance is destroyed """
        self.stop()

    def _tw_alive_rpc(self):
        """ start a RPC server so the SMQ server can check if this client is still alive """
        self._alive_rpc_server = SimpleXMLRPCServer(('', 0), allow_none=True, logRequests=False)
        self._alive_rpc_server.register_function(lambda: True, name='is_alive')
        while not self._shutdown:
            self._alive_rpc_server.handle_request()
        self._alive_rpc_server = None

    def _tw_process_message(self, msg):
        """ process an incoming message by delegating to the handler and returning a response

            Args:
                msg - message to process
        """
        logging.info(f'received msg - {msg["msg_type"]}')
        # handle if a response
        if 'response_payload' in msg:
            if msg['msg_uuid'] in self._response_callbacks:
                handler = self._response_callbacks[msg['msg_uuid']]
                del self._response_callbacks[msg['msg_uuid']]
                if handler is not None:
                    handler(msg, self)
            return

        # handle a normal message
        handler = self._message_handlers.get(msg['msg_type'], None)
        if handler:
            retval = handler(msg, self)
        else:
            retval = None
        self.send_message(SMQ_Client.construct_response_msg(msg, retval))

    def _tw_pump_messages(self):
        """ thread worker which will create new threads to handle each incoming message """
        # flag for reconnect needed
        need_reconnect = False

        while not self._shutdown:
            try:
                if need_reconnect:
                    logging.info(f'Reconnecting {self._client_name} {self._client_id} {self._classification} ' +
                                 f'{self._pub_list} {self._sub_list}')
                    with xmlrpc.client.ServerProxy(self._smq_server_url, allow_none=True) as sp:
                        sp.register_client(self._client_name, self._client_id, self._classification, self._pub_list_extended,
                                           self._sub_list_extended, self._alive_rpc_server.server_address[1], self._tag)
                    need_reconnect = False
                    time.sleep(1)

                with xmlrpc.client.ServerProxy(self._smq_server_url, allow_none=True) as sp:
                    msg = sp.pop_message(self._client_id)
                if msg is not None:
                    t = threading.Thread(target=self._tw_process_message, args=[msg], daemon=True)
                    t.start()
                else:
                    time.sleep(self._polling_interval)
            except ConnectionRefusedError:
                logging.warning(f'SMQ Server at {self._smq_server_url} is refusing connection')
                time.sleep(5)
                need_reconnect = True
            except Exception as e:
                logging.exception(e)
                time.sleep(5)

    def add_message_handler(self, msg_type, handler):
        """ add a handler function that will be called when a message of msg_type is received

            Args:
                msg_type - type of message to bind this handler to.  If a handler already exists for this message type
                           it will be overwritten by the new handler.  There can only be one handler for a message type
                handler - handler function for the msg_type.  Prototype for the handler is f(msg)
        """
        if msg_type not in self._sub_list:
            raise Exception(f'Message type "{msg_type}" is not on this SMQ Client\'s subscription list')

        self._message_handlers[msg_type] = handler

    def construct_msg(self, msg_type, target_id, payload, msg_uuid=None, sender_id=None):
        """ construct a message for the Simple Message Queue

            Args:
                msg_type - type of message, i.e. 'reload_config'
                target_id - client id of the recipient of this message, use '*' for a broadcast to everyone
                payload - dictionary containing the data for this message, the structure of the dict is unique to each
                          msg_type
                msg_uuid - unique id of this message, no two messages can ever share the same uuid.  If none, a uuid
                           will be generated
                sender_id - client id of the sender of this message.  If none, the client_id of this SMQ_Client will be
                            used

            Returns:
                dict containing the message
        """
        if msg_uuid is None:
            msg_uuid = uuid.uuid4().hex
        if sender_id is None:
            sender_id = self._client_id

        return {'msg_type': msg_type, 'msg_uuid': msg_uuid, 'target_id': target_id, 'sender_id': sender_id,
                'payload': payload}

    @classmethod
    def construct_response_msg(cls, og_msg, response_payload):
        """ construct a response to a message for the Simple Message Queue

            Args:
                og_msg - original message being responded to
                response_payload - dictionary containing the response data to the original message

            Returns:
                dict containing the message
        """
        return {'msg_type': og_msg['msg_type'] + '_response', 'msg_uuid': og_msg['msg_uuid'],
                'target_id': og_msg['sender_id'], 'sender_id': og_msg['target_id'], 'payload': og_msg['payload'],
                'response_payload': response_payload}

    def get_info_for_all_clients(self):
        """ Proxy to the SMQ Server call get_info_for_all_clients.  See the SQM Server documentation for more details

            The SMQ Client does not need to be started to call this function
        """
        with xmlrpc.client.ServerProxy(self._smq_server_url, allow_none=True) as sp:
            client_info = sp.get_info_for_all_clients()
        logging.info(f'get_info_for_all_clients')
        for k, v in client_info.items():
            logging.info(f'    {k}: {v}')
        return client_info

    def is_alive(self, client_id):
        try:
            with xmlrpc.client.ServerProxy(self._smq_server_url, allow_none=True) as sp:
                return sp.is_alive(client_id)
        except Exception as e:
            logging.exception(e)

    def remove_message_handler(self, msg_type):
        """ remove the message handler for a message type

            Args:
                msg_type - message type to remove the handler for

            Returns:
                the handler that was assigned to the message type before removal
        """
        if msg_type not in self._sub_list:
            raise Exception(f'Message type "{msg_type}" is not on this SMQ Client\'s subscription list')

        return self._message_handlers.pop(msg_type, None)

    def send_message(self, msg, response_callback=None, wait=0):
        """ send a message constructed by construct_msg to its recipient

            Args:
                msg - message to send
                response_callback - handler that will be called when response is received from the recipient after
                                    processing the message.  Must be None if wait is non-zero.
                wait - if 0, no response handling will happen.  Otherwise the number of seconds to wait for the response
                       before throwing a timeout exception

            Returns:
                if wait is 0, then None.  Otherwise the response payload will be returned
        """
        if msg['msg_type'] not in self._pub_list_extended:
            raise Exception(f'Message type "{msg["msg_type"]}" is not on this SMQ Client\'s publication list {msg}')

        # blocking response handler if wait != 0
        response_msg, response_returned = None, False

        def response_handler(msg, smqc):
            nonlocal response_msg, response_returned
            response_msg, response_returned = msg, True

        if wait != 0:
            response_callback = response_handler

        # log and setup the response_callback
        logging.info(f'Sending {msg["msg_uuid"]} {msg["msg_type"]} {msg["payload"]} ' +
                     f'from {msg["sender_id"]} to {msg["target_id"]}')
        self._response_callbacks[msg['msg_uuid']] = response_callback

        # send the message
        with xmlrpc.client.ServerProxy(self._smq_server_url, allow_none=True) as sp:
            sp.send_message(msg)

        # handle wait != 0
        if wait != 0:
            start_time = time.time()
            while not response_returned:
                if time.time() - start_time > wait:
                    raise TimeoutError()
                time.sleep(0.1)
            return response_msg['response_payload']

    def start(self):
        """ start the SMQ Client """
        logging.info(f'Starting {self._client_name} {self._client_id} {self._classification} {self._pub_list} ' +
                     f'{self._sub_list}')
        threading.Thread(target=self._tw_alive_rpc, daemon=True).start()
        time.sleep(1)
        with xmlrpc.client.ServerProxy(self._smq_server_url, allow_none=True) as sp:
            sp.register_client(self._client_name, self._client_id, self._classification, self._pub_list_extended,
                               self._sub_list_extended, self._alive_rpc_server.server_address[1], self._tag)
        threading.Thread(target=self._tw_pump_messages, daemon=True).start()
        self._started = True

    def stop(self, force=False):
        """ stop the SMQ Client """
        if self._started or force:
            logging.info(f'Stopping {self._client_name} {self._client_id}')
            self._shutdown = True
            with xmlrpc.client.ServerProxy(self._smq_server_url, allow_none=True) as sp:
                sp.unregister_client(self._client_id)
