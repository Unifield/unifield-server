# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

# A histogram with 10 buckets and a range of 9 has the following max
# value for each bucket:
# 0: 1  range/(buckets-1) * bucketnum+1 = 9/9 * 0+1 = 1
# ...
# 8: 9  9/9 * 8+1 = 9
# 9: inf

class Histogram:
    def __init__(self, **kw):
        buckets = kw.get('buckets', 10)
        # a histogram with one bucket would result in div by zero
        assert buckets >= 2
        
        self._range = kw.get('range', 9)
        self._scale = float(self._range)/float(buckets-1)
        self.name = kw.get('name', '')
        
        self.buckets = [0]*buckets
        self.limits = [0]*buckets
        for i in range(buckets-1):
            self.limits[i] = '%.4g' % (self._scale * (i+1))
        # The limit of the last bucket is infinity
        self.limits[buckets-1] = 'inf'
        
    def _bnum(self, x):
        assert x >= 0
        if x > self._range:
            return len(self.buckets)-1
        return int(float(x)/self._scale)
    
    def add(self, x):
        assert x >= 0
        bnum = self._bnum(x)
        assert bnum < len(self.buckets), "bnum %d" % bnum
        self.buckets[bnum] += 1

    def clear(self):
        self.buckets = [0]*len(self.buckets)
        
if __name__ == '__main__':
    import unittest
    class TestHistogram(unittest.TestCase):
        def test_limits(self):
            h = Histogram( range=100 )
            h.add(0)
            with self.assertRaises(AssertionError):
                h.add(-1)
            h.add(99)
            h.add(100)
            h.add(101)
            assert h.buckets == [ 1, 0, 0, 0, 0,
                                  0, 0, 0, 1, 2 ]
        def test_2_bucket(self):
            h = Histogram( buckets=2, range=1 )
            h.add(0)
            h.add(9999)
            assert h.buckets == [ 1, 1 ]
            h.clear()
            assert h.buckets == [ 0, 0 ]
            
            
        def test_float(self):
            h = Histogram( range=1 )
            h.add(0)
            h.add(0)
            h.add(0.5)
            h.add(0.5)
            h.add(1.1)
            h.add(1.1)
            assert h.buckets == [ 2, 0, 0, 0, 2,
                                  0, 0, 0, 0, 2 ]
            assert h.limits == ['0.1111', '0.2222', '0.3333', '0.4444', '0.5556', '0.6667', '0.7778', '0.8889', '1', 'inf']
            
    unittest.main()
