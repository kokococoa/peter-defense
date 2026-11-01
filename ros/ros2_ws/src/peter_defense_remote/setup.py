from setuptools import find_packages, setup

setup(
    name='peter_defense_remote', version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/peter_defense_remote']),
        ('share/peter_defense_remote', ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Peter Defense', maintainer_email='maintainer@example.com',
    description='Remote USB camera compressed image publisher', license='Apache-2.0',
    entry_points={'console_scripts': [
        'camera_publisher = peter_defense_remote.camera_publisher:main',
    ]},
)
