`NmtBase.state` should always return a `str`
## Problem

`NmtBase.state` is documented and annotated as always returning a string, however there is a code path that may return an `int`:

[链接已移除]

The code path in question is highly unlikely; the `NmtBase._state` member is set in the following places:

- ✅ `NmtBase.__init__`: explicitly set to 0
- ✅ `NmtBase.on_command`: set _iff_ the new state is a valid/known state
- ✅ `NmtBase.send_command`: set _iff_ the new state is a valid/known state
- ❓ `NmtMaster.on_heartbeat`: set to whatever was decoded from the heartbeat message, which _should_ be fine for any compliant device

## Possible solutions

In `NmtMaster.on_heartbeat`, only set `_state` if it is a valid state; if it's not, `log.error(...)` or raise an exception.

In `NmtBase.state`, either raise an exception if `._state` is not a valid state, or return something a la `f"UNKNOWN STATE {self._state}"`.

<details>
<summary>Draft diff</summary>

```diff
diff --git a/canopen/nmt.py b/canopen/nmt.py
index 401ad15..1316a5c 100644
--- a/canopen/nmt.py
+++ b/canopen/nmt.py
@@ -86,10 +86,8 @@ class NmtBase:
         - 'RESET'
         - 'RESET COMMUNICATION'
         """
-        if self._state in NMT_STATES:
-            return NMT_STATES[self._state]
-        else:
-            return self._state
+        assert self._state in NMT_STATES:
+        return NMT_STATES[self._state]
 
     @state.setter
     def state(self, new_state: str):
@@ -122,6 +120,12 @@ class NmtMaster(NmtBase):
             logger.debug("Received heartbeat can-id %d, state is %d", can_id, new_state)
             for callback in self._callbacks:
                 callback(new_state)
+            if new_state not in NMT_STATES:
+                log.error(
+                    "Received heartbeat can-id %d with invalid state %d",
+                    can_id, new_state
+                )
+                return
             if new_state == 0:
                 # Boot-up, will go to PRE-OPERATIONAL automatically
                 self._state = 127
```

</details>
