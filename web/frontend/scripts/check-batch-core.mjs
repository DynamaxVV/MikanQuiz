import assert from 'node:assert/strict';
import { rectFromPoints, invalidateRegion, matchesReviewFilter, regionProblem, updateDifficulty } from '../src/lib/batchDrafts.ts';

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
// A ready region must be able to move directly from two stars to one star.
region.status = 'ready';
region.form.difficulty = 2;
const difficultySelect = { currentTarget: { value: '1' } };
assert.equal(updateDifficulty(region, Number(difficultySelect.currentTarget.value)), true);
assert.equal(region.form.difficulty, 1);
assert.equal(region.status, 'draft');
assert.equal(updateDifficulty(region, 3), true);
assert.equal(updateDifficulty(region, 1), true);
assert.equal(region.form.difficulty, 1);
region.status = 'saved';
assert.equal(updateDifficulty(region, 2), false);
assert.equal(region.form.difficulty, 1);
assert.equal(matchesReviewFilter('saved', 'saved'), true);
assert.equal(matchesReviewFilter('ready', 'pending'), true);
assert.equal(matchesReviewFilter('pending', 'pending'), true);
assert.equal(matchesReviewFilter('draft', 'pending'), false);
assert.equal(matchesReviewFilter('draft', 'draft'), true);
assert.equal(matchesReviewFilter('deleted', 'deleted'), true);
console.log('Batch geometry, validation and immutable pending-request checks passed.');
