ESLProtocol.stop: Socket is not cleaned up if socket is closed
When  `ESLProtocol.stop()` is called, it issues a `socket.send`, but it will raise an exception if socket is already closed

```ruby
mai 12 18:17:41: Traceback (most recent call last):
mai 12 18:17:41:   File "src/gevent/_abstract_linkable.py", line 267, in gevent._gevent_c_abstract_linkable.AbstractLinkable._notify_link_list
mai 12 18:17:41:   File "<retracted>/server.py", line 60, in _handle_call_finish
mai 12 18:17:41:     super()._handle_call_finish(handler)
mai 12 18:17:41:   File "<retracted>/python/greenswitch/esl.py", line 610, in _handle_call_finish
mai 12 18:17:41:     handler.session.stop()
mai 12 18:17:41:   File "<retracted>/python/greenswitch/esl.py", line 219, in stop
mai 12 18:17:41:     self.send('exit')
mai 12 18:17:41:   File "<retracted>/python/greenswitch/esl.py", line 213, in send
mai 12 18:17:41:     response = async_response.get()
mai 12 18:17:41:   File "src/gevent/event.py", line 329, in gevent._gevent_cevent.AsyncResult.get
mai 12 18:17:41:   File "src/gevent/event.py", line 359, in gevent._gevent_cevent.AsyncResult.get
mai 12 18:17:41:   File "src/gevent/event.py", line 347, in gevent._gevent_cevent.AsyncResult.get
mai 12 18:17:41:   File "src/gevent/event.py", line 327, in gevent._gevent_cevent.AsyncResult._raise_exception
mai 12 18:17:41:   File "<retracted>/python/gevent/_compat.py", line 66, in reraise
mai 12 18:17:41:     raise value
mai 12 18:17:41: greenswitch.esl.OutboundSessionHasGoneAway

```

The socket will stay in `CLOSE_WAIT` leaking fle descriptors

```ruby
TCP 172.31.8.212:5000->172.31.27.86:60468 (CLOSE_WAIT)
TCP 172.31.8.212:5000->172.31.27.86:45630 (CLOSE_WAIT)
TCP 172.31.8.212:5000->172.31.27.86:47444 (CLOSE_WAIT)
TCP 172.31.8.212:5000->172.31.8.212:60844 (CLOSE_WAIT)
TCP 172.31.8.212:5000->172.31.27.86:51948 (CLOSE_WAIT)
```

The offeding code is:
```python
class ESLProtocol(object):
    # ...
    def stop(self):
        if self.connected:
            try:
                self.send('exit')
            except (NotConnectedError, socket.error):
                pass
        self._run = False
        if self._receive_events_greenlet:
            logging.info("Waiting for receive greenlet exit")
            self._receive_events_greenlet.join()
        if self._process_events_greenlet:
            logging.info("Waiting for event processing greenlet exit")
            self._process_events_greenlet.join()
        self.sock.close()
        self.sock_file.close()
```

IMHO, I think that `try/except` is incomplete, it should handle `OutboundSessionHasGoneAway` too
