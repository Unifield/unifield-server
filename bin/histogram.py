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
        self.buckets = [0]*buckets
        self.name = kw.get('name', '')
        if 'range' in kw:
            self._range = kw.get('range')
            self._scale = float(self._range)/float(len(self.buckets)-1)
            self._auto_range = False
        else:
            self._range = None
            self._auto_range = True

    def limits(self):
        assert self._scale is not None
        buckets = len(self.buckets)
        limits = [''] * buckets
        for i in range(buckets-1):
            limits[i] = '%.4g' % (self._scale * (i+1))
        # The limit of the last bucket is infinity
        limits[buckets-1] = 'inf'
        return limits

    def _bnum(self, x):
        assert x >= 0
        if self._range is None:
            # We are configured for auto-range. This is
            # the first sample, so use it to set the range. We assume
            # that this sample is representative of the values we'll see.
            # So we set the range so that this sample lands in the
            # middle of the histogram, leaving room above and below it
            # to observe other samples.
            if x == 0:
                # Do not allow a zero range, which would result in
                # a zero scale and div-by-zero.
                x0 = 1
            else:
                x0 = x
            self._range = x0/2.5 * 5.0
            self._scale = float(self._range)/float(len(self.buckets)-1)
            assert self._scale != 0

        if x > self._range:
            return len(self.buckets)-1
        return int(float(x)/self._scale)

    def add(self, x):
        if x >= 0:
            bnum = self._bnum(x)
            self.buckets[bnum] += 1

    def clear(self):
        self.buckets = [0]*len(self.buckets)
        assert isinstance(self.buckets[0], int)
        if self._auto_range:
            self._range = None

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
            assert h._auto_range == False
            h.add(0)
            h.add(0)
            h.add(0.5)
            h.add(0.5)
            h.add(1.1)
            h.add(1.1)
            assert h.buckets == [ 2, 0, 0, 0, 2,
                                  0, 0, 0, 0, 2 ], h.buckets
            assert h.limits() == ['0.1111', '0.2222', '0.3333', '0.4444', '0.5556', '0.6667', '0.7778', '0.8889', '1', 'inf']
            h.clear()
            h.add(0)
            h.add(0)
            assert h.buckets == [ 2, 0, 0, 0, 0,
                                  0, 0, 0, 0, 0 ], h.buckets
            assert h.limits() == ['0.1111', '0.2222', '0.3333', '0.4444', '0.5556', '0.6667', '0.7778', '0.8889', '1', 'inf']

        def test_auto_range(self):
            h = Histogram()
            h.add(1)
            h.add(0.01)
            h.add(20)
            assert h.buckets == [1, 0, 0, 0, 1, 0, 0, 0, 0, 1]
            assert h.limits() == ['0.2222', '0.4444', '0.6667', '0.8889', '1.111', '1.333', '1.556', '1.778', '2', 'inf']
            # check that add after limits does not give an error
            # (previously did due to aliasing bug)
            h.add(20)

            h.clear()
            h.add(20)
            h.add(0.01)
            h.add(1)
            assert h.buckets == [2, 0, 0, 0, 1, 0, 0, 0, 0, 0]
            assert h.limits() == ['4.444', '8.889', '13.33', '17.78', '22.22', '26.67', '31.11', '35.56', '40', 'inf']

    unittest.main()
