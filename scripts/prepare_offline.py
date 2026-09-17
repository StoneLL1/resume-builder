"""Prepare pinned runtime artifacts on a connected machine for offline installation."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import bootstrap_runtime as runtime


def artifacts(manifest, platform, template=None, all_fonts=False):
    selected = runtime.scoped_manifest(manifest, template, all_fonts)
    items = [selected['python']['platforms'][platform], selected['typst']['platforms'][platform]]
    items += [font.get('archive', font) for font in selected['fonts']['files']]
    return list({item['filename']: item for item in items}.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', required=True, choices=sorted(runtime.PLATFORMS))
    parser.add_argument('--output', type=Path)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--template')
    scope.add_argument('--all-fonts', action='store_true')
    parser.add_argument('--list', action='store_true', help='Print the manifest; do not download')
    parser.add_argument('--mirror')
    args = parser.parse_args()
    manifest = runtime.load_manifest(runtime.DEFAULT_MANIFEST)
    items = artifacts(manifest, args.platform, args.template, args.all_fonts)
    if args.list:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    if args.output is None:
        parser.error('--output is required unless --list is used')
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        for item in items:
            cached = runtime.download(item, runtime.runtime_home() / 'downloads', args.mirror)
            destination = args.output.resolve() / item['filename']
            if cached.resolve() != destination:
                shutil.copy2(cached, destination)
        (args.output / 'artifacts.json').write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
        shutil.copy2(runtime.ROOT / 'assets/runtime-NOTICES.md', args.output / 'runtime-NOTICES.md')
    except (runtime.BootstrapError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f'Offline artifacts ready: {args.output.resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
