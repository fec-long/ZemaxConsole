import unittest
from console import Model, build, DEMO


class Tests(unittest.TestCase):
    def test_demo(self):
        model, zpl, output = build(DEMO)
        self.assertEqual(len(model.surfaces), 2)
        self.assertEqual(model.surfaces[-1].thickness, 45)
        self.assertIn('SURP 1, 2, 0.02', zpl)
        self.assertIn('SURP 2, 2, -0.02', zpl)
        self.assertIn('SURP 1, 6, 12.5', zpl)
        self.assertEqual(zpl.count('INSERT '), 1)

    def test_loop_and_repeat(self):
        source = 'for r in [50,80]:\n    add_lens(r,-r,5,20)\n    add_space(10)'
        a, z, _ = build(source)
        self.assertEqual(len(a.surfaces), 4)
        self.assertEqual(z.count('INSERT '), 3)
        self.assertEqual(z, build(source)[1])

    def test_invalid_geometry(self):
        for args in [(5,-5,5,25), (50,-50,0.1,25), (50,-50,5,-1)]:
            with self.assertRaises(ValueError):
                Model().add_lens(*args)

    def test_planes_and_material_validation(self):
        m = Model()
        m.add_lens(float('inf'), 0, 5, 25)
        self.assertIn('SURP 1, 2, 0', m.zpl())
        with self.assertRaises(ValueError):
            m.add_lens(50,-50,5,25, 'bad"\nINSERT 9')
        with self.assertRaises(ValueError):
            m.add_space(float('nan'))

    def test_empty_and_failure(self):
        with self.assertRaises(ValueError):
            build('print("empty")')
        with self.assertRaises(SyntaxError):
            build('for')
        with self.assertRaises(ValueError):
            Model().add_space(1)


if __name__ == '__main__':
    unittest.main()
