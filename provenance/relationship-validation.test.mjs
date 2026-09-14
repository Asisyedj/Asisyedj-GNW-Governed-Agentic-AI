import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const readJson = (name) => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
const source = readJson('source-identity.json');
const digests = readJson('artifact-digests.json');
const relationships = readJson('relationship-verification.json');
const release = readJson('release-manifest.json');

const outerSha = '68162c182cc411f5449811c156beda560bf59272ae2ec2529d28d1381ef077de';
const embeddedSha = '446cb463dd07092be870a1a3456c50c1efc6d3414a088480af89e74c470fa6d1';
const commitSha = 'e0e3c415314044e62ca451461462d22a6aaa9aa9';
const treeSha = '2917faa6d994365ca29a708484968ee13009c1c2';
const lockSha = 'd652675f2651efcec306e02ccffa5725863d138f593448bb7394018a5fd96e5e';

assert.equal(source.repository.commit_sha, commitSha);
assert.equal(source.repository.tree_sha, treeSha);
assert.equal(source.objects.outer_source_bundle.sha256, outerSha);
assert.equal(source.objects.embedded_frozen_archive.sha256, embeddedSha);
assert.equal(source.objects.package_lock.sha256, lockSha);
assert.equal(release.source_commit, commitSha);
assert.equal(release.source_tree, treeSha);
assert.equal(release.PRODUCTION_RELEASE, 'DENIED');
assert.equal(release.INTERNATIONAL_CERTIFICATION, 'NOT_CLAIMED');
assert.notEqual(outerSha, embeddedSha);

const rel = relationships.relationships;
const hasRelation = (from, relation, to, acceptableStatuses) => rel.some((item) =>
  item.from === from && item.relation === relation && item.to === to && acceptableStatuses.includes(item.status));
assert.equal(hasRelation('outer_source_bundle', 'CONTAINS', 'embedded_frozen_archive', ['VERIFIED']), true);
assert.equal(hasRelation('source_tree', 'AT_COMMIT', 'git_commit', ['VERIFIED']), true);
assert.equal(hasRelation('package_lock', 'PART_OF', 'source_tree', ['VERIFIED']), true);

const artifactIds = new Set(digests.artifacts.map((item) => item.id));
for (const id of ['outer_source_bundle', 'embedded_frozen_archive', 'git_commit', 'git_tree', 'package_lock', 'sbom', 'build_artifact', 'container_image', 'provenance']) {
  assert.equal(artifactIds.has(id), true, `missing artifact identity: ${id}`);
}
assert.equal(release.objects.sbom.status, 'UNAVAILABLE');
assert.equal(release.objects.provenance.status, 'UNAVAILABLE');
assert.equal(release.verification.independent_review, 'BLOCKED');

const expectReject = (label, fn) => {
  assert.throws(fn, undefined, `${label} must reject`);
};
expectReject('wrong archive hash', () => assert.equal(source.objects.outer_source_bundle.sha256, 'wrong'));
expectReject('wrong commit', () => assert.equal(source.repository.commit_sha, 'wrong'));
expectReject('altered manifest', () => assert.equal(release.PRODUCTION_RELEASE, 'ALLOWED'));
expectReject('missing relationship', () => assert.equal(hasRelation('outer_source_bundle', 'CONTAINS', 'missing', ['VERIFIED']), true));
expectReject('substituted SBOM', () => assert.equal(release.objects.sbom.sha256, 'not-a-real-digest'));
expectReject('missing provenance', () => assert.equal(release.objects.provenance.status, 'AVAILABLE'));
expectReject('mismatched artifact digest', () => assert.equal(digests.artifacts.find((item) => item.id === 'package_lock').sha256, 'wrong'));

console.log('PASS: Phase 1 source identity and relationship validation');
console.log('PASS: outer and embedded archive identities remain distinct');
console.log('PASS: unavailable SBOM/build/provenance states remain fail-closed');
console.log('PASS: seven tamper/substitution negative checks rejected');
