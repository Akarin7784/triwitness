get_binding method raises a TypeError if called too early in charm lifecycle
## Bug
If the `self.model.get_binding()` is called too early in a charms lifecycle it raises a `TypeError`. This error is unexpected and is not documented in the `ops.model` docstrings. It would be OK return an empty result or even raise a known documented exception, but `TypeError` seems out of place.

## Traceback
For example when `get_binding()` is invoked in the first `config_changed` event, a traceback such as the following results
```
application-prometheus: 14:08:42 ERROR unit.prometheus/0.juju-log Uncaught exception while in charm code:
Traceback (most recent call last):
  File "./src/charm.py", line 369, in <module>
    main(PrometheusCharm)
  File "/var/lib/juju/agents/unit-prometheus-0/charm/venv/ops/main.py", line 406, in main
    _emit_charm_event(charm, dispatcher.event_name)
  File "/var/lib/juju/agents/unit-prometheus-0/charm/venv/ops/main.py", line 140, in _emit_charm_event
    event_to_emit.emit(*args, **kwargs)
  File "/var/lib/juju/agents/unit-prometheus-0/charm/venv/ops/framework.py", line 278, in emit
    framework._emit(event)
  File "/var/lib/juju/agents/unit-prometheus-0/charm/venv/ops/framework.py", line 722, in _emit
    self._reemit(event_path)
  File "/var/lib/juju/agents/unit-prometheus-0/charm/venv/ops/framework.py", line 767, in _reemit
    custom_handler(event)
  File "./src/charm.py", line 48, in _on_config_changed
    self.ingress_address()
  File "./src/charm.py", line 359, in ingress_address
    ingress = str(self.model.get_binding('prometheus').network.ingress_address)
  File "/var/lib/juju/agents/unit-prometheus-0/charm/venv/ops/model.py", line 523, in network
    self._network = Network(self._backend.network_get(self.name, self._relation_id))
  File "/var/lib/juju/agents/unit-prometheus-0/charm/venv/ops/model.py", line 562, in __init__
    for address_info in interface_info.get('addresses', []):
TypeError: 'NoneType' object is not iterable
application-prometheus: 14:08:42 ERROR juju.worker.caasoperator.uniter.prometheus/0.operation hook "config-changed" (via hook dispatching script: dispatch) failed: exit status 1
```

## Notes
The bug was triaged by @jameinel and he pointed out "from the traceback it looks like the code was trying to do "If it doesn't exist replace it with an empty list", but in actuality it does exist but with a content of None. So we just need to change it to:"
```
addrs = ...get()
if addrs is not None:
  for addr in addrs:
```
