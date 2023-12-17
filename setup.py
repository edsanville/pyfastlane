from setuptools import setup

setup(name='pyfastlane',
      version='0.1',
      description='Build and deliver iOS apps using fastlane',
      url='',
      author='Ed Sanville',
      author_email='edsanville@gmail.com',
      license='GPL',
      scripts=[
            'scripts/pyfastlane.py',
      ],
      packages=['appPublish'],
      install_requires=[
      ],
      zip_safe=False)
