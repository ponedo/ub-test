#!/usr/bin/env python3
"""Pure scope tests; no simulator."""
import unittest
from small import allowed_missing
class Scope(unittest.TestCase):
    def test_exact_whitelist(self):
        m={'continuation_contract':'fixed3136-v04-window-and-v09-only'}
        for row,arm,gap in [('V04','v1','streaming_physical'),('V04','candidate-on','streaming_physical'),('C-V04','candidate-off','streaming_physical'),('V09','candidate-on','stale_grant')]:
            self.assertTrue(allowed_missing({'id':row},arm,[gap],m))
            self.assertFalse(allowed_missing({'id':row},arm,[gap,'resource_cleanup'],m))
            self.assertFalse(allowed_missing({'id':row},arm,[gap],{}))
        for row,arm,gap in [('S64','v1','streaming_physical'),('S64','candidate-on','streaming_physical'),('V09','v1','stale_grant'),('V08','candidate-on','ta_window_512'),('V05','v1','streaming_physical')]:
            self.assertFalse(allowed_missing({'id':row},arm,[gap],m))
if __name__=='__main__':unittest.main()
