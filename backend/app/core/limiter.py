from slowapi import Limiter
from slowapi.util import get_remote_address

# D-07: in-memory store, no Redis dependency at this stage.
# Redis-backed rate limiting deferred to Phase 4 (multi-worker deployment).
limiter = Limiter(key_func=get_remote_address)
