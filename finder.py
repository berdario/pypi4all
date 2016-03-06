import hashlib
from urllib.request import urlopen
from io import BytesIO
import zipfile
import tarfile
import json
from itertools import chain
import sys
import codecs

utf8reader = codecs.getreader("utf-8")

from pkg_resources import evaluate_marker, parse_requirements, split_sections

from pip.req import InstallRequirement
from pip.index import PackageFinder
from pip.download import PipSession

from setup_sanitizer import extract_from_setup

session = PipSession()
finder = PackageFinder([], ['https://pypi.python.org/simple'], session=session)

def munge(rqr):
    return chain.from_iterable(
        [parse_requirements(reqset['requires']) for reqset in rqr
                if not reqset.get('environment')
                or evaluate_marker(reqset['environment'])])

    
def parse_metadata(metadata):
    return json.load(utf8reader(metadata))['run_requires']
    
def parse_requirestxt(requires):
    return [{'requires': reqset, 'environment': env[1:] if env else env}
                for env, reqset in split_sections(requires)]

def download_pkg(pkgname, constraint):
    link = finder.find_requirement(InstallRequirement.from_line(pkgname), True)
    with urlopen(link.url) as u:
        pkgarchive = BytesIO(u.read())
    check_hash(link, pkgarchive.getbuffer())
    return link, pkgarchive

def extract_dependencies_from_tar(archiveobj, pkgname, versionedpkg):
    requires_path = '%s/%s.egg-info/requires.txt' % (versionedpkg, pkgname)
    try:
        with archiveobj.extractfile(requires_path) as requires:
            return munge(parse_requirestxt(requires))
    except KeyError:
        setuppy_path = '%s/setup.py' % versionedpkg
        with archiveobj.extractfile(setuppy_path) as setuppy:
            return extract_from_setup(setuppy_path, setuppy)

def find_dependencies(pkgname, constraint):
    link, pkgarchive = download_pkg(pkgname, constraint)
    versionedpkg =  '-'.join(link.splitext()[0].split('-')[:2])
    if link.ext == '.whl':
        with zipfile.ZipFile(pkgarchive) as zf:
            with zf.open(versionedpkg + '.dist-info/metadata.json') as metadata:
                return munge(parse_metadata(metadata))
    elif link.ext == '.tar.gz':
        with tarfile.open(fileobj=pkgarchive) as archiveobj:
            return extract_dependencies_from_tar(archiveobj, pkgname, versionedpkg)
    else:
        raise Exception('unexpected extension %s' % link.ext)
       

def check_hash(link, content):
    return getattr(hashlib, link.hash_name)(content).hexdigest() == link.hash


if __name__ == '__main__':
    pkg = sys.argv[1]
    print(list(find_dependencies(pkg, '')))