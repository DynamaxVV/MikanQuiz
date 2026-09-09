import assert from 'node:assert/strict';
import { rectFromPoints, invalidateRegion, regionProblem } from '../src/lib/batchDrafts.ts';

assert.deepEqual(rectFromPoints({ x: 500.2, y: 400 }, { x: -10, y: 80 }, 300, 250), { x: 0, y: 80, width: 300, height: 170 });
const region = { id: 'region', x: 0, y: 0, width: 40, height: 60, status: 'ready', preview: 'preview', uploadUrl: 'old-upload',
  form: { text: '题干', imageUrl: null, difficulty: 1, correctOptionId: '1', explanation: '解析' } };
assert.equal(regionProblem(region, [{ id: '1', minimumDifficulty: 2 }]), '正确字体的最低难度高于本题难度');
invalidateRegion(region);
assert.equal(region.status, 'draft');
assert.equal(region.uploadUrl, undefined);
region.status = 'pending'; region.uploadUrl = 'locked-upload';
invalidateRegion(region);
assert.equal(region.status, 'pending');
assert.equal(region.uploadUrl, 'locked-upload');
assert.equal(regionProblem(region, [{ id: '1', minimumDifficulty: 1 }]), '');
console.log('Batch geometry, validation and immutable pending-request checks passed.');
