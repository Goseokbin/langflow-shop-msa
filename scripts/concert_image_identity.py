"""Concert image identity shared by package inventory and vulnerability ingestion."""
import copy
import re
import uuid
import urllib.parse


def identity(name, digest=None):
    name = name.strip()
    if '@' in name:
        name, embedded = name.rsplit('@', 1)
        if digest and embedded != digest:
            raise ValueError('Image digest mismatch')
        digest = embedded
    if not digest or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('A pinned sha256 image digest is required')
    # Only the final path segment can contain a tag. Preserve registry ports.
    head, sep, tail = name.rpartition('/')
    tail = tail.split(':', 1)[0]
    name = head + sep + tail
    for prefix in ('docker.io/', 'index.docker.io/', 'registry-1.docker.io/'):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    if '/' not in name:
        if '.' in name or ':' in name:
            raise ValueError('Registry without a repository is not an image')
        name = 'library/' + name
    if not name or any(c.isspace() for c in name):
        raise ValueError('Invalid image repository')
    return name, digest


def select_artifact(artifacts, name, digest):
    key = identity(name, digest)
    matches = []
    for art in artifacts:
        try:
            if identity(art['name'], art['digest']) == key:
                matches.append(art)
        except ValueError:
            continue
    # Prefer the canonical spelling; never fall back to digest alone.
    exact = [a for a in matches if a['name'] == key[0]]
    if len(exact) == 1:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f'Expected one artifact for {key[0]}@{digest}; found {len(matches)}')


def normalize_sbom(source, name, digest):
    name, digest = identity(name, digest)
    if source.get('bomFormat') != 'CycloneDX':
        raise ValueError('Only CycloneDX image reports are accepted; raw Trivy JSON splits registry ports')
    result = copy.deepcopy(source)
    result['serialNumber'] = 'urn:uuid:' + str(uuid.uuid4())
    comp = result.setdefault('metadata', {}).setdefault('component', {})
    old_ref = comp.get('bom-ref')
    ref = name + '@' + digest
    comp.update({'name': ref, 'bom-ref': ref})
    if comp.get('purl', '').startswith('pkg:oci/'):
        base, _, query = comp['purl'].partition('?')
        qualifiers = dict(urllib.parse.parse_qsl(query))
        qualifiers['repository_url'] = name
        comp['purl'] = base + '?' + urllib.parse.urlencode(sorted(qualifiers.items()), safe=':')
    # Rewrite only references to the root image, preserving package identities.
    for dep in result.get('dependencies', []):
        if old_ref and dep.get('ref') == old_ref:
            dep['ref'] = ref
        dep['dependsOn'] = [ref if old_ref and x == old_ref else x for x in dep.get('dependsOn', [])]
    for vuln in result.get('vulnerabilities', []):
        for affect in vuln.get('affects', []):
            if old_ref and affect.get('ref') == old_ref:
                affect['ref'] = ref
    return result
