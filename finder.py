from pip.req import InstallRequirement
from pip.index import PackageFinder

f = PackageFinder([], ['https://pypi.python.org/simple'])
f.find_requirement(InstallRequirement.from_line('requests'), True)
