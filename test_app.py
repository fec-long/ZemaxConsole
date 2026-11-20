import unittest, multiprocessing as mp
from app import worker
import legacy
import sys
sys.modules['console']=legacy
from test_legacy import Tests

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.c, child=mp.Pipe(); self.p=mp.Process(target=worker,args=(child,)); self.p.start(); child.close()
    def tearDown(self): self.p.terminate(); self.p.join(); self.c.close()
    def run_code(self,source):
        self.c.send(source); result=[]
        while True:
            self.assertTrue(self.c.poll(10),'worker timeout'); msg=self.c.recv(); result.append(msg)
            if msg[0] in ('done','error'): return result
    def test_persistent_state(self):
        self.assertEqual(self.run_code('x=12')[-1],('done',''))
        result=self.run_code('print(x)\nadd_lens(50,-50,5,20)\nadd_space(x)')
        self.assertIn(('output','12'),result); self.assertIn('SURP 2, 3, 12',result[-1][1])
    def test_output_before_error(self):
        result=self.run_code('print("before")\n1/0')
        self.assertIn(('output','before'),result); self.assertIn('ZeroDivisionError',result[-1][1])
        self.assertEqual(self.run_code('x=1')[-1][0],'done')
    def test_original_line_numbers(self):
        self.assertIn('line 6',self.run_code('\n'*5+'raise ValueError("bad")')[-1][1])
if __name__=='__main__': mp.freeze_support(); unittest.main()
