from setuptools import setup, find_packages

README = open('README.rst').read()

setup(name="crane-ec2",
      version="0.1.7",
      description="helper library to service related api actions in ec2 ",
      long_description=README,
      author="timeredbull",
      author_email="timeredbull@corp.globo.com",
      packages=find_packages(exclude=['docs', 'tests']),
      include_package_data=True,
      install_requires=["django==1.4.1", "boto==2.5.2"],
      tests_require=["nose==1.1.2", "django_nose==1.1", "mocker==1.1.1"]
)
