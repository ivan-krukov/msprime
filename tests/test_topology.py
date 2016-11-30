#
# Copyright (C) 2016 Jerome Kelleher <jerome.kelleher@well.ox.ac.uk>
#
# This file is part of msprime.
#
# msprime is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# msprime is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with msprime.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Test cases for the supported topological variations and operations.
"""
from __future__ import print_function
from __future__ import division

import unittest

import msprime
import _msprime


def build_tree_sequence(records, mutations=[]):
    ts = _msprime.TreeSequence()
    ts.load_records(records)
    ts.set_mutations(mutations)
    return msprime.TreeSequence(ts)


def insert_redundant_breakpoints(ts):
    """
    Builds a new tree sequence containing redundant breakpoints.
    """
    new_records = []
    for r in ts.records():
        x = r.left + (r.right - r.left) / 2
        new_records.append(msprime.CoalescenceRecord(
            left=r.left, right=x, children=r.children, node=r.node,
            population=r.population, time=r.time))
        new_records.append(msprime.CoalescenceRecord(
            left=x, right=r.right, children=r.children, node=r.node,
            population=r.population, time=r.time))
    new_ts = build_tree_sequence(new_records)
    assert new_ts.num_records == 2 * ts.num_records
    return new_ts


class TopologyTestCase(unittest.TestCase):
    """
    Superclass of test cases containing common utilities.
    """
    random_seed = 123456

    def assert_haplotypes_equal(self, ts1, ts2):
        h1 = list(ts1.haplotypes())
        h2 = list(ts2.haplotypes())
        self.assertEqual(h1, h2)

    def assert_variants_equal(self, ts1, ts2):
        v1 = list(ts1.variants(as_bytes=True))
        v2 = list(ts2.variants(as_bytes=True))
        self.assertEqual(v1, v2)


class TestRecordSquashing(TopologyTestCase):
    """
    Tests that we correctly squash adjacent equal records together.
    """
    def test_single_record(self):
        records = [
            msprime.CoalescenceRecord(
                left=0, right=1, node=2, children=(0, 1), time=1, population=0),
            msprime.CoalescenceRecord(
                left=1, right=2, node=2, children=(0, 1), time=1, population=0),
        ]
        ts = build_tree_sequence(records)
        self.assertEqual(list(ts.records()), records)
        tss = ts.simplify()
        simplified_records = list(tss.records())
        self.assertEqual(len(simplified_records), 1)
        r = simplified_records[0]
        self.assertEqual(r.left, 0)
        self.assertEqual(r.right, 2)

    def test_single_tree(self):
        ts = msprime.simulate(10, random_seed=self.random_seed)
        ts_redundant = insert_redundant_breakpoints(ts)
        tss = ts_redundant.simplify()
        self.assertEqual(list(tss.records()), list(ts.records()))

    def test_many_trees(self):
        ts = msprime.simulate(20, recombination_rate=5, random_seed=self.random_seed)
        self.assertGreater(ts.num_trees, 2)
        ts_redundant = insert_redundant_breakpoints(ts)
        tss = ts_redundant.simplify()
        self.assertEqual(list(tss.records()), list(ts.records()))


class TestRedundantBreakpoints(TopologyTestCase):
    """
    Tests for dealing with redundant breakpoints within the tree sequence.
    These are records that may be squashed together into a single record.
    """
    def test_single_tree(self):
        ts = msprime.simulate(10, random_seed=self.random_seed)
        ts_redundant = insert_redundant_breakpoints(ts)
        self.assertEqual(ts.sample_size, ts_redundant.sample_size)
        self.assertEqual(ts.sequence_length, ts_redundant.sequence_length)
        self.assertEqual(ts_redundant.num_trees, 2)
        trees = [t.parent_dict for t in ts_redundant.trees()]
        self.assertEqual(len(trees), 2)
        self.assertEqual(trees[0], trees[1])
        self.assertEqual([t.parent_dict for t in ts.trees()][0], trees[0])

    def test_many_trees(self):
        ts = msprime.simulate(20, recombination_rate=5, random_seed=self.random_seed)
        self.assertGreater(ts.num_trees, 2)
        ts_redundant = insert_redundant_breakpoints(ts)
        self.assertEqual(ts.sample_size, ts_redundant.sample_size)
        self.assertEqual(ts.sequence_length, ts_redundant.sequence_length)
        self.assertGreater(ts_redundant.num_trees, ts.num_trees)
        self.assertGreater(ts_redundant.num_records, ts.num_records)
        redundant_trees = ts_redundant.trees()
        redundant_t = next(redundant_trees)
        comparisons = 0
        for t in ts.trees():
            while redundant_t is not None and redundant_t.interval[1] <= t.interval[1]:
                self.assertEqual(t.parent_dict, redundant_t.parent_dict)
                comparisons += 1
                redundant_t = next(redundant_trees, None)
        self.assertEqual(comparisons, ts_redundant.num_trees)


class TestUnaryNodes(TopologyTestCase):
    """
    Tests for situations in which we have unary nodes in the tree sequence.
    """
    def test_simple_case(self):
        # Simple case where we have n = 2 and some unary nodes.
        records = [
            msprime.CoalescenceRecord(
                left=0, right=1, node=2, children=(0,), time=1, population=0),
            msprime.CoalescenceRecord(
                left=0, right=1, node=3, children=(1,), time=1, population=0),
            msprime.CoalescenceRecord(
                left=0, right=1, node=4, children=(2, 3), time=2, population=0),
            msprime.CoalescenceRecord(
                left=0, right=1, node=5, children=(4,), time=3, population=0),
        ]
        mutations = [(j * 1 / 5, j) for j in range(5)]
        ts = build_tree_sequence(records, mutations)
        self.assertEqual(ts.sample_size, 2)
        self.assertEqual(ts.num_nodes, 6)
        self.assertEqual(ts.num_trees, 1)
        t = next(ts.trees())
        self.assertEqual(
            t.parent_dict, {0: 2, 1: 3, 2: 4, 3: 4, 4: 5})
        self.assertEqual(t.mrca(0, 1), 4)
        self.assertEqual(t.mrca(0, 2), 2)
        self.assertEqual(t.mrca(0, 4), 4)
        self.assertEqual(t.mrca(0, 5), 5)
        self.assertEqual(t.mrca(0, 3), 4)
        H = list(ts.haplotypes())
        self.assertEqual(H[0], "10101")
        self.assertEqual(H[1], "01011")

    def test_ladder_tree(self):
        # We have a single tree with a long ladder of unary nodes along a path
        num_unary_nodes = 50
        n = 2
        records = [
            msprime.CoalescenceRecord(
                left=0, right=1, node=n, children=(0,), time=1, population=0)]
        for j in range(num_unary_nodes):
            records.append(
                msprime.CoalescenceRecord(
                    left=0, right=1, node=n + j + 1, children=(n + j,), time=j + 2,
                    population=0))
        root = num_unary_nodes + 3
        root_time = num_unary_nodes + 3
        records.append(
            msprime.CoalescenceRecord(
               left=0, right=1, node=root, children=(1, num_unary_nodes + 2),
               time=root_time, population=0))
        ts = build_tree_sequence(records)
        t = next(ts.trees())
        self.assertEqual(t.mrca(0, 1), root)
        self.assertEqual(t.tmrca(0, 1), root_time)
        ts_simplified = ts.simplify()
        self.assertEqual(ts_simplified.num_records, 1)
        t = next(ts_simplified.trees())
        self.assertEqual(t.mrca(0, 1), 2)
        self.assertEqual(t.tmrca(0, 1), root_time)

    def verify_unary_tree_sequence(self, ts):
        """
        Take the specified tree sequence and produce an equivalent in which
        unary records have been interspersed.
        """
        self.assertGreater(ts.num_trees, 2)
        self.assertGreater(ts.num_mutations, 2)
        new_records = []
        next_node = ts.num_nodes
        for r in ts.records():
            u = r.node
            t = r.time - 1e-14  # Arbitrary small value.
            children = []
            for v in r.children:
                new_records.append(msprime.CoalescenceRecord(
                    left=r.left, right=r.right, population=r.population,
                    node=next_node, children=(v,), time=t))
                children.append(next_node)
                next_node += 1
            new_records.append(msprime.CoalescenceRecord(
                left=r.left, right=r.right, population=r.population,
                node=u, children=tuple(children), time=r.time))
        new_records.sort(key=lambda r: r.time)
        ts_new = build_tree_sequence(new_records, list(ts.mutations()))
        self.assertGreater(ts_new.num_records, ts.num_records)
        self.assert_haplotypes_equal(ts, ts_new)
        self.assert_variants_equal(ts, ts_new)
        ts_simplified = ts_new.simplify()
        self.assertEqual(list(ts_simplified.records()), list(ts.records()))
        self.assert_haplotypes_equal(ts, ts_simplified)
        self.assert_variants_equal(ts, ts_simplified)

    def test_binary_tree_sequence_unary_nodes(self):
        ts = msprime.simulate(
            20, recombination_rate=5, mutation_rate=5, random_seed=self.random_seed)
        self.verify_unary_tree_sequence(ts)

    def test_nonbinary_tree_sequence_unary_nodes(self):
        demographic_events = [
            msprime.SimpleBottleneck(time=1.0, proportion=0.95)]
        ts = msprime.simulate(
            20, recombination_rate=10, mutation_rate=5,
            demographic_events=demographic_events, random_seed=self.random_seed)
        found = False
        for r in ts.records():
            if len(r.children) > 2:
                found = True
        self.assertTrue(found)
        self.verify_unary_tree_sequence(ts)


class TestNonSampleExternalNodes(TopologyTestCase):
    """
    Tests for situations in which we have unary nodes in the tree sequence.
    """
    def test_simple_case(self):
        # Simplest case where we have n = 2 and external non-sample nodes.
        records = [
            msprime.CoalescenceRecord(
                left=0, right=1, node=2, children=(0, 1, 3, 4), time=1, population=0),
        ]
        ts = build_tree_sequence(records)
        self.assertEqual(ts.sample_size, 2)
        self.assertEqual(ts.num_trees, 1)
        self.assertEqual(ts.num_nodes, 5)
        t = next(ts.trees())
        self.assertEqual(t.parent_dict, {0: 2, 1: 2, 3: 2, 4: 2})
        self.assertEqual(t.time_dict, {0: 0, 1: 0, 3: 0, 4: 0, 2: 1})
        self.assertEqual(t.root, 2)
        ts_simplified = ts.simplify()
        self.assertEqual(ts_simplified.num_nodes, 3)
        self.assertEqual(ts_simplified.num_trees, 1)
        t = next(ts_simplified.trees())
        self.assertEqual(t.parent_dict, {0: 2, 1: 2})
        self.assertEqual(t.time_dict, {0: 0, 1: 0, 2: 1})
        self.assertEqual(t.root, 2)

    def test_unary_non_sample_external_nodes(self):
        # Take an ordinary tree sequence and put a bunch of external non
        # sample nodes on it.
        ts = msprime.simulate(
            15, recombination_rate=5, random_seed=self.random_seed, mutation_rate=5)
        self.assertGreater(ts.num_trees, 2)
        self.assertGreater(ts.num_mutations, 2)
        new_records = []
        next_node = ts.num_nodes
        for r in ts.records():
            children = tuple(list(r.children) + [next_node])
            new_records.append(msprime.CoalescenceRecord(
                left=r.left, right=r.right, node=r.node, time=r.time,
                population=r.population, children=children))
            next_node += 1
        ts_new = build_tree_sequence(new_records, list(ts.mutations()))
        self.assertEqual(ts_new.num_nodes, next_node)
        self.assertEqual(ts_new.sample_size, ts.sample_size)
        # FIXME disabled until leaf-lists on these nodes is fixed.
        # self.assert_haplotypes_equal(ts, ts_new)
        # self.assert_variants_equal(ts, ts_new)
        ts_simplified = ts_new.simplify()
        self.assertEqual(ts_simplified.num_nodes, ts.num_nodes)
        self.assertEqual(ts_simplified.sample_size, ts.sample_size)
        self.assertEqual(list(ts_simplified.records()), list(ts.records()))
        self.assert_haplotypes_equal(ts, ts_simplified)
        self.assert_variants_equal(ts, ts_simplified)
