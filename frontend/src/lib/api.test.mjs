import test from 'node:test';
import assert from 'node:assert/strict';

test('url joins api prefix', () => {
  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  assert.equal(`${API}/signals`, 'http://localhost:8000/api/v1/signals');
});
