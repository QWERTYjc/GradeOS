import test from 'node:test';
import assert from 'node:assert/strict';
import { Budget, parseStudentBudget } from '../src/core.mjs';

test('explicit student budget admits full output plus input reservation within aggregate cap', () => {
  const cap = parseStudentBudget('0.5', 2);
  const reservation = 20000 * 0.5 / 1e6 + 100000 * 0.125 / 1e6;
  assert.throws(() => new Budget({ cap: 2, scopeCap: 0.01 }).admit(reservation, { budget_scope: 'student-a' }), /Per-student budget/);
  const budget = new Budget({ cap: 2, scopeCap: cap });
  assert.doesNotThrow(() => budget.admit(reservation, { budget_scope: 'student-a' }));
  assert.throws(() => budget.admit(0.5, { budget_scope: 'student-a' }), /Per-student budget/);
  assert.throws(() => budget.admit(2, { lane: 'main' }), /Budget reservation limit/);
});

test('student budget rejects invalid amounts and cannot exceed the aggregate limit', () => {
  for (const value of ['', '0', '-1', 'Infinity', 'NaN', '3', undefined]) {
    assert.throws(() => parseStudentBudget(value, 2), /Per-student budget/);
  }
  assert.equal(parseStudentBudget('0.01', 2), 0.01);
  assert.equal(parseStudentBudget('2', 2), 2);
});
