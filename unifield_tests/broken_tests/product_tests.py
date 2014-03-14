'''
Created on Feb 28, 2014

@author: qt
'''
import unittest

from tests_config.unifield_test import UnifieldTest

class ProductTest(UnifieldTest):

    def getOrCreateUoM(self, instance, name='PCE'):
        """
        Search the UoM named like the 'name' parameter
        or create it.
        """
        uom_id = instance.uom.search([('name', '=', name)])

        if not uom_id:
            uom_id = instance.uom.create({
                'name': name,
            })

        return uom_id

    def createNewProduct(self, instance, code, name, special_vals=None):
        """
        Create a new product. This methed defines some
        default values than can be overrided by the
        special_vals parameter.
        """
        values = {
            'supply_method': 'buy',
            'standard_price': 1.00,
            'uom_id': self.getOrCreateUoM(instance),
            'name': name,
            'uom_po_id': self.getOrCreateUoM(instance),
            'type': 'product',
            'procure_method': 'make_to_order',
            'cost_method': 'average',

        }

    def setUp(self):
        super(ProductTest, self).setUp()

        # Get or create products at Project side
        # Get or create products at Coordo side
        # Get or create products at HQ side

    def getProducts(self, domain, p_type):
        p1_p_ids = self.c1p1.product.search(domain)
        self.assert_(p1_p_ids, 'No %s product found in P1' % p_type)

        c1_p_ids = self.c1.product.search(domain)
        self.assert_(c1_p_ids, 'No %s product found in C1' % p_type)

        hq1_p_ids = self.hq1.product.search(domain)
        self.asset_(hq1_p_ids, 'No %s product fond in HQ1' % p_type)

        return p1_p_ids[0], c1_p_ids[0], hq1_p_ids[0]

    def getStandardProduct(self):
        product_domain = [
            ('type', '=', 'product'),
            ('subtype', '=', 'single'),
            ('batch_management', '=', False),
            ('perishable', '=', False),
        ]
        res = self.getProducts(product_domain, 'standard')

        self.products['project'].setdefault('standard', res[0])
        self.products['coordo'].setdefault('standard', res[1])
        self.products['hq'].setdefault('standard', res[2])

    def getConsumableProduct(self):
        product_domain = [
            ('type', '=', 'consu'),
            ('batch_management', '=', False),
            ('perishable', '=', False),
        ]
        res = self.getProducts(product_domain, 'consumable')

        self.products['project'].setdefault('consumable', res[0])
        self.products['coordo'].setdefault('consumable', res[1])
        self.products['hq'].setdefault('consumable', res[2])

    def getServiceProduct(self):
        product_domain = [
            ('type', '=', 'service'),
            ('batch_management', '=', False),
            ('perishable', '=', False),
        ]
        res = self.getProducts(product_domain, 'service')

        self.products['project'].setdefault('service', res[0])
        self.products['coordo'].setdefault('service', res[1])
        self.products['hq'].setdefault('service', res[2])


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
